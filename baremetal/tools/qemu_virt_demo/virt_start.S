# tools/qemu_virt_demo/virt_start.S — QEMU virt 演示的极简入口：设栈顶 → call main。
# 直接从 RAM(0x80000000) 执行，无 flash→ram 数据拷贝需求，故不清 .data/.bss。
# （生产固件的完整启动在 boot/crt0.S；此处为 board-matched 演示的最简变体。）
    .section .text
    .global _start
_start:
    la   sp, _estack
    /* 复位 gp：兼容 virt_a.ld（定义了 __global_pointer$）；基线 virt.ld 未定义
       该符号也不使用 .sdata 松弛，不受影响。norelax 保证本条不被松弛改写。 */
    .option push
    .option norelax
    la   gp, __global_pointer$
    .option pop
    call main
1:  j    1b
