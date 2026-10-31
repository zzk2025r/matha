/* tools/qemu_virt_demo/virt_a.ld — 路线 A：QEMU virt 单一 RAM、VMA==LMA 布局。
 *
 * 设计口径（与同目录生产演示基线 virt.ld 同址 0x80000000，见 baremetal/README）：
 *   - QEMU virt 在 0x80000000 起只有一整块普通 RAM：无 flash、rv32 virt 亦无可用
 *     PMP 强制，故不做「FLASH(rx)/RAM(rw)」假分区——MEMORY 的 rx/rw 仅供链接器
 *     记账，不产生运行时权限；fake `AT` 拷移反而引入 LMA 溢出 VMA 的隐患。
 *   - 全部段 VMA==LMA：.data 无需搬移，但符号契约（include/hal/boot.h +
 *     tools/check_skeleton.py 的 LD_MUST_HAVE）仍完整给出；_sidata == _sdata
 *     使 crt0 的搬移循环成为无害 no-op（换真 FE310 时只需把 text/rodata 改投
 *     FLASH 区并给 .data 加回 AT，即退化为生产 link.ld 语义）。
 *   - 入口取 .text.entry 内第一条指令 = _start（crt0.S / virt_start.S 契约），
 *     绝不 ENTRY(main)（裸机无 OS 设栈）。
 *   - 栈顶 _estack = RAM 窗口末端向下生长；NOLOAD .heap 从 bss 末到窗口末，
 *     与中间预留的 4K 栈区共同构成增长空间（allocator 读 [_heap_start,_heap_end)）。
 *   - __global_pointer$ 锚定 .sdata 起点 + 0x800（前置 0x800 偏移使 ±2KB 松弛
 *     窗口恰好覆盖 .data/.sdata）；消费方须在启动时 `la gp, __global_pointer$`
 *     （配 .option norelax），仅定义符号不复位寄存器 = 运行期必炸。
 */
ENTRY(_start)

MEMORY
{
    RAM (rwx) : ORIGIN = 0x80000000, LENGTH = 1M
}

SECTIONS
{
    . = ORIGIN(RAM);

    /* 代码 + 只读数据（同一 RAM 窗口内取指执行，非 flash XIP） */
    .text : {
        KEEP(*(.text.entry))        /* _start 必须位于段首（链接器从首个段取入口） */
        *(.text .text.*)
    } >RAM

    .rodata : {
        *(.rodata .rodata.*)
        . = ALIGN(4);
    } >RAM

    /* .data：VMA==LMA，无拷移；_sidata=_sdata 令 crt0 拷贝循环自然空转 */
    .data : {
        _sdata = .;
        *(.data .data.*)
        *(.sdata .sdata.*)
        _edata = .;
        . = ALIGN(4);
    } >RAM
    _sidata = _sdata;
    __global_pointer$ = _sdata + 0x800;

    .bss (NOLOAD) : {
        _sbss = .;
        *(.bss .bss.*)
        *(.sbss .sbss.*)
        *(COMMON)
        _ebss = .;
        . = ALIGN(8);               /* allocator 要求 8 字节对齐 payload */
    } >RAM

    /* 栈：向下生长，栈顶 = RAM 窗口末端（与 virt.ld 的 0x80100000 同值） */
    _estack = ORIGIN(RAM) + LENGTH(RAM);

    /* 堆：[_heap_start, _heap_end) 向上生长，预留 4K 给栈 */
    .heap (NOLOAD) : {
        . = ALIGN(8);
        _heap_start = .;
        _heap_end = _estack - 4K;
    } >RAM

    /DISCARD/ : {
        *(.comment) *(.note*) *(riscv.attributes)
    }
}
